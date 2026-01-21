#!/usr/bin/env bash
# Test KubeCodeRun sidecar execution in a real Kubernetes environment
# Uses the same security settings as production Helm deployments
#
# Usage: ./scripts/test-k8s-sidecar.sh [OPTIONS]
#
# Options:
#   -t, --tag TAG        Image tag to test (default: latest)
#   -r, --registry REG   Registry prefix (e.g., aronmuon/kubecoderun)
#   -n, --namespace NS   Kubernetes namespace (default: default)
#   -c, --context CTX    Kubernetes context (default: docker-desktop)
#   -l, --language LANG  Test only specified language (can repeat)
#   -v, --verbose        Show detailed output
#   --keep-pods          Don't delete pods after testing (for debugging)
#   -h, --help           Show this help message
#
# Prerequisites:
#   - kubectl configured with access to a Kubernetes cluster
#   - Docker images available (Docker Desktop K8s shares local images)
#   - curl and jq installed

set -euo pipefail

# Defaults
TAG="latest"
PREFIX="kcr"  # Local image prefix (matches build-images.sh)
REGISTRY=""   # When set, overrides PREFIX
NAMESPACE="default"
CONTEXT="docker-desktop"
VERBOSE=false
KEEP_PODS=false
SPECIFIC_LANGS=()

# Track original context for restoration
ORIGINAL_CONTEXT=""

# Test configuration
EXPECTED_OUTPUT="Hello, KubeCodeRun!"
SIDECAR_PORT=8080
POD_TIMEOUT=120  # seconds to wait for pod ready
EXEC_TIMEOUT=30  # seconds for code execution

# Cleanup tracking
CREATED_PODS=()
PORT_FORWARD_PIDS=()

# Test code for each language (same as test-images.sh)
declare -A TEST_CODE
TEST_CODE[py]='print("Hello, KubeCodeRun!")'
TEST_CODE[js]='console.log("Hello, KubeCodeRun!");'
TEST_CODE[ts]='console.log("Hello, KubeCodeRun!");'
TEST_CODE[go]='package main

import "fmt"

func main() {
    fmt.Println("Hello, KubeCodeRun!")
}'
TEST_CODE[java]='public class Code {
    public static void main(String[] args) {
        System.out.println("Hello, KubeCodeRun!");
    }
}'
TEST_CODE[c]='#include <stdio.h>

int main() {
    printf("Hello, KubeCodeRun!\n");
    return 0;
}'
TEST_CODE[cpp]='#include <iostream>

int main() {
    std::cout << "Hello, KubeCodeRun!" << std::endl;
    return 0;
}'
TEST_CODE[php]='<?php
echo "Hello, KubeCodeRun!\n";'
TEST_CODE[rs]='fn main() {
    println!("Hello, KubeCodeRun!");
}'
TEST_CODE[r]='cat("Hello, KubeCodeRun!\n")'
TEST_CODE[f90]='program hello
    print *, "Hello, KubeCodeRun!"
end program hello'
TEST_CODE[d]='import std.stdio;

void main() {
    writeln("Hello, KubeCodeRun!");
}'

# Language display names
declare -A LANG_NAMES
LANG_NAMES[py]="Python"
LANG_NAMES[js]="JavaScript"
LANG_NAMES[ts]="TypeScript"
LANG_NAMES[go]="Go"
LANG_NAMES[java]="Java"
LANG_NAMES[c]="C"
LANG_NAMES[cpp]="C++"
LANG_NAMES[php]="PHP"
LANG_NAMES[rs]="Rust"
LANG_NAMES[r]="R"
LANG_NAMES[f90]="Fortran"
LANG_NAMES[d]="D"

# Image names for each language
declare -A LANG_IMAGE
LANG_IMAGE[py]=python
LANG_IMAGE[js]=nodejs
LANG_IMAGE[ts]=nodejs
LANG_IMAGE[go]=go
LANG_IMAGE[java]=java
LANG_IMAGE[c]=c-cpp
LANG_IMAGE[cpp]=c-cpp
LANG_IMAGE[php]=php
LANG_IMAGE[rs]=rust
LANG_IMAGE[r]=r
LANG_IMAGE[f90]=fortran
LANG_IMAGE[d]=d

# Sidecar language identifiers (what the sidecar expects in LANGUAGE env var)
declare -A LANG_SIDECAR_ID
LANG_SIDECAR_ID[py]=python
LANG_SIDECAR_ID[js]=javascript
LANG_SIDECAR_ID[ts]=typescript
LANG_SIDECAR_ID[go]=go
LANG_SIDECAR_ID[java]=java
LANG_SIDECAR_ID[c]=c
LANG_SIDECAR_ID[cpp]=cpp
LANG_SIDECAR_ID[php]=php
LANG_SIDECAR_ID[rs]=rust
LANG_SIDECAR_ID[r]=r
LANG_SIDECAR_ID[f90]=fortran
LANG_SIDECAR_ID[d]=d

usage() {
    head -n 18 "$0" | tail -n 16 | sed 's/^# //'
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--tag)
                TAG="$2"
                shift 2
                ;;
            -r|--registry)
                REGISTRY="$2"
                shift 2
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -c|--context)
                CONTEXT="$2"
                shift 2
                ;;
            -l|--language)
                SPECIFIC_LANGS+=("$2")
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --keep-pods)
                KEEP_PODS=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

log() {
    if [[ "$VERBOSE" == true ]]; then
        echo "[DEBUG] $*"
    fi
}

error() {
    echo "[ERROR] $*" >&2
}

cleanup() {
    echo ""
    echo "Cleaning up..."

    # Kill port-forward processes
    for pid in "${PORT_FORWARD_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done

    # Delete created pods
    if [[ "$KEEP_PODS" == false ]]; then
        for pod in "${CREATED_PODS[@]}"; do
            log "Deleting pod: $pod"
            kubectl delete pod "$pod" -n "$NAMESPACE" --ignore-not-found --wait=false &>/dev/null || true
        done
    else
        echo "Keeping pods for debugging. Clean up manually with:"
        for pod in "${CREATED_PODS[@]}"; do
            echo "  kubectl delete pod $pod -n $NAMESPACE"
        done
    fi

    # Restore original kubectl context
    if [[ -n "$ORIGINAL_CONTEXT" && "$ORIGINAL_CONTEXT" != "$CONTEXT" ]]; then
        echo "Restoring kubectl context to: $ORIGINAL_CONTEXT"
        kubectl config use-context "$ORIGINAL_CONTEXT" &>/dev/null || true
    fi
}

check_prerequisites() {
    local missing=()

    # Check for required commands
    for cmd in kubectl curl jq nc; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required commands: ${missing[*]}"
        exit 1
    fi

    # Save original context for restoration
    ORIGINAL_CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")

    # Switch to target context if different
    if [[ -n "$CONTEXT" && "$CONTEXT" != "$ORIGINAL_CONTEXT" ]]; then
        echo "Switching kubectl context: $ORIGINAL_CONTEXT -> $CONTEXT"
        if ! kubectl config use-context "$CONTEXT" &>/dev/null; then
            error "Failed to switch to context '$CONTEXT'"
            error "Available contexts: $(kubectl config get-contexts -o name | tr '\n' ' ')"
            exit 1
        fi
    fi

    # Check kubectl connectivity
    if ! kubectl cluster-info &>/dev/null; then
        error "Cannot connect to Kubernetes cluster. Is kubectl configured?"
        exit 1
    fi

    # Check namespace exists
    if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
        error "Namespace '$NAMESPACE' does not exist"
        exit 1
    fi

    log "Prerequisites check passed"
}

get_full_image_name() {
    local image_name="$1"
    if [[ -n "$REGISTRY" ]]; then
        echo "${REGISTRY}-${image_name}:${TAG}"
    elif [[ -n "$PREFIX" ]]; then
        echo "${PREFIX}-${image_name}:${TAG}"
    else
        echo "${image_name}:${TAG}"
    fi
}

get_sidecar_image() {
    if [[ -n "$REGISTRY" ]]; then
        echo "${REGISTRY}-sidecar:${TAG}"
    elif [[ -n "$PREFIX" ]]; then
        echo "${PREFIX}-sidecar:${TAG}"
    else
        echo "sidecar:${TAG}"
    fi
}

# Generate pod manifest with production security settings
# Matches src/services/kubernetes/client.py create_pod_manifest()
generate_pod_manifest() {
    local pod_name="$1"
    local main_image="$2"
    local sidecar_image="$3"
    local language="$4"

    cat <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: ${pod_name}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: kubecoderun-test
    app.kubernetes.io/component: execution
    kubecoderun.io/language: ${language}
    kubecoderun.io/type: test
spec:
  # Critical: share process namespace so sidecar can use nsenter
  shareProcessNamespace: true
  restartPolicy: Never
  terminationGracePeriodSeconds: 10

  # Pod-level security context
  securityContext:
    fsGroup: 65532
    # Seccomp profile - same as production
    seccompProfile:
      type: RuntimeDefault

  volumes:
    - name: shared-data
      emptyDir:
        sizeLimit: 1Gi

  containers:
    # Main container (language runtime)
    - name: main
      image: ${main_image}
      imagePullPolicy: Never
      workingDir: /mnt/data
      volumeMounts:
        - name: shared-data
          mountPath: /mnt/data
      resources:
        limits:
          cpu: "1"
          memory: 512Mi
        requests:
          cpu: 100m
          memory: 128Mi
      securityContext:
        runAsUser: 65532
        runAsGroup: 65532
        runAsNonRoot: true
        allowPrivilegeEscalation: false
        capabilities:
          drop:
            - ALL
      env:
        - name: HOME
          value: /mnt/data

    # Sidecar container (HTTP API for execution)
    - name: sidecar
      image: ${sidecar_image}
      imagePullPolicy: Never
      ports:
        - containerPort: ${SIDECAR_PORT}
          name: http
      volumeMounts:
        - name: shared-data
          mountPath: /mnt/data
      resources:
        limits:
          cpu: 500m
          memory: 512Mi
        requests:
          cpu: 100m
          memory: 256Mi
      # Sidecar needs elevated privileges for nsenter
      # See client.py comments for detailed explanation
      securityContext:
        runAsUser: 65532
        runAsGroup: 65532
        runAsNonRoot: true
        allowPrivilegeEscalation: true  # Required for file capabilities
        capabilities:
          add:
            - SYS_PTRACE   # Access /proc/<pid>/ns/
            - SYS_ADMIN    # Call setns() to enter namespaces
            - SYS_CHROOT   # Mount namespace operations
          drop:
            - ALL
      env:
        - name: LANGUAGE
          value: ${language}
        - name: WORKING_DIR
          value: /mnt/data
        - name: SIDECAR_PORT
          value: "${SIDECAR_PORT}"
      readinessProbe:
        httpGet:
          path: /ready
          port: ${SIDECAR_PORT}
        initialDelaySeconds: 2
        periodSeconds: 2
        timeoutSeconds: 5
        failureThreshold: 30
      livenessProbe:
        httpGet:
          path: /health
          port: ${SIDECAR_PORT}
        initialDelaySeconds: 5
        periodSeconds: 10
        timeoutSeconds: 5
        failureThreshold: 3
EOF
}

# Find an available local port
find_available_port() {
    local port
    # Try to find an available port in the ephemeral range
    for port in $(seq 10000 10100); do
        if ! nc -z localhost "$port" 2>/dev/null; then
            echo "$port"
            return 0
        fi
    done
    # Fallback: let the system assign
    echo "0"
}

wait_for_pod_ready() {
    local pod_name="$1"
    local timeout="$2"

    log "Waiting for pod $pod_name to be ready..."

    if kubectl wait --for=condition=Ready "pod/$pod_name" -n "$NAMESPACE" --timeout="${timeout}s" &>/dev/null; then
        return 0
    else
        return 1
    fi
}

execute_code_via_sidecar() {
    local port="$1"
    local code="$2"
    local timeout="$3"

    local response
    local http_code

    # Make HTTP request to sidecar
    response=$(curl -s -w "\n%{http_code}" \
        --connect-timeout 5 \
        --max-time "$((timeout + 10))" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$(jq -n --arg code "$code" --argjson timeout "$timeout" '{code: $code, timeout: $timeout, working_dir: "/mnt/data"}')" \
        "http://localhost:${port}/execute" 2>&1) || true

    http_code=$(echo "$response" | tail -1)
    response=$(echo "$response" | sed '$d')

    if [[ "$http_code" != "200" ]]; then
        echo "HTTP_ERROR:$http_code:$response"
        return 1
    fi

    echo "$response"
    return 0
}

test_language() {
    local lang="$1"
    local name="${LANG_NAMES[$lang]}"
    local code="${TEST_CODE[$lang]}"
    local image_name="${LANG_IMAGE[$lang]}"
    local sidecar_lang="${LANG_SIDECAR_ID[$lang]}"

    local main_image
    main_image=$(get_full_image_name "$image_name")
    local sidecar_image
    sidecar_image=$(get_sidecar_image)

    local pod_name="test-sidecar-${lang}-$(date +%s)"

    printf "%-12s %-20s " "[$lang]" "$name"

    # Generate and apply pod manifest
    local manifest
    manifest=$(generate_pod_manifest "$pod_name" "$main_image" "$sidecar_image" "$sidecar_lang")

    log "Creating pod $pod_name"
    if ! echo "$manifest" | kubectl apply -f - &>/dev/null; then
        echo "FAIL (pod creation failed)"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Manifest:"
            echo "$manifest" | head -20
        fi
        return 1
    fi

    CREATED_PODS+=("$pod_name")

    # Wait for pod to be ready
    if ! wait_for_pod_ready "$pod_name" "$POD_TIMEOUT"; then
        echo "FAIL (pod not ready within ${POD_TIMEOUT}s)"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Pod status:"
            kubectl get pod "$pod_name" -n "$NAMESPACE" -o wide
            echo "  Pod events:"
            kubectl describe pod "$pod_name" -n "$NAMESPACE" | grep -A 20 "Events:"
        fi
        return 1
    fi

    # Start port-forward
    local local_port
    local_port=$(find_available_port)

    log "Starting port-forward on port $local_port"
    kubectl port-forward "pod/$pod_name" -n "$NAMESPACE" "${local_port}:${SIDECAR_PORT}" &>/dev/null &
    local pf_pid=$!
    PORT_FORWARD_PIDS+=("$pf_pid")

    # Wait for port-forward to be ready
    local wait_count=0
    while ! nc -z localhost "$local_port" 2>/dev/null; do
        sleep 0.2
        wait_count=$((wait_count + 1))
        if [[ $wait_count -gt 50 ]]; then
            echo "FAIL (port-forward not ready)"
            return 1
        fi
    done

    # Execute code via sidecar HTTP API
    log "Executing code via sidecar..."
    local result
    result=$(execute_code_via_sidecar "$local_port" "$code" "$EXEC_TIMEOUT") || true

    # Kill port-forward
    kill "$pf_pid" 2>/dev/null || true

    # Check for HTTP errors
    if [[ "$result" == HTTP_ERROR:* ]]; then
        echo "FAIL (sidecar error)"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Response: $result"
            echo "  Pod logs (sidecar):"
            kubectl logs "$pod_name" -n "$NAMESPACE" -c sidecar --tail=20 2>/dev/null || true
        fi
        return 1
    fi

    # Parse response
    local exit_code stdout stderr
    exit_code=$(echo "$result" | jq -r '.exit_code // 1')
    stdout=$(echo "$result" | jq -r '.stdout // ""')
    stderr=$(echo "$result" | jq -r '.stderr // ""')

    # Normalize output (trim whitespace, handle Fortran's leading space)
    local normalized_output
    normalized_output=$(echo "$stdout" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | head -1)

    if [[ "$exit_code" != "0" ]]; then
        echo "FAIL (exit code: $exit_code)"
        if [[ "$VERBOSE" == true ]]; then
            echo "  stdout: $stdout"
            echo "  stderr: $stderr"
            echo "  Pod logs (sidecar):"
            kubectl logs "$pod_name" -n "$NAMESPACE" -c sidecar --tail=20 2>/dev/null || true
        fi
        return 1
    elif [[ "$normalized_output" != "$EXPECTED_OUTPUT" ]]; then
        echo "FAIL (output mismatch)"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Expected: '$EXPECTED_OUTPUT'"
            echo "  Got:      '$normalized_output'"
            echo "  Full stdout: $stdout"
        fi
        return 1
    else
        echo "PASS"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Output: $normalized_output"
            local exec_time
            exec_time=$(echo "$result" | jq -r '.execution_time_ms // "?"')
            echo "  Execution time: ${exec_time}ms"
        fi
        return 0
    fi
}

main() {
    parse_args "$@"

    # Set up cleanup trap
    trap cleanup EXIT

    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║       KubeCodeRun Kubernetes Sidecar Tester              ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  Tag:       ${TAG}"
    if [[ -n "$REGISTRY" ]]; then
        echo "║  Registry:  ${REGISTRY}"
    fi
    echo "║  Namespace: ${NAMESPACE}"
    echo "║  Cluster:   $(kubectl config current-context 2>/dev/null || echo 'unknown')"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""

    check_prerequisites

    # Determine which languages to test
    local langs_to_test
    if [[ ${#SPECIFIC_LANGS[@]} -gt 0 ]]; then
        langs_to_test=("${SPECIFIC_LANGS[@]}")
    else
        langs_to_test=(py js ts go java c cpp php rs r f90 d)
    fi

    local passed=0
    local failed=0
    local skipped=0
    local failed_langs=()

    echo "Running sidecar tests..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for lang in "${langs_to_test[@]}"; do
        if [[ -z "${LANG_IMAGE[$lang]:-}" ]]; then
            echo "Unknown language: $lang"
            continue
        fi

        local result=0
        test_language "$lang" || result=$?

        case $result in
            0) passed=$((passed + 1)) ;;
            1) failed=$((failed + 1)); failed_langs+=("$lang") ;;
            2) skipped=$((skipped + 1)) ;;
        esac
    done

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Summary
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                     Test Summary                         ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  Passed:   ${passed}"
    echo "║  Failed:   ${failed}"
    echo "║  Skipped:  ${skipped}"
    echo "╚══════════════════════════════════════════════════════════╝"

    if [[ ${#failed_langs[@]} -gt 0 ]]; then
        echo ""
        echo "Failed languages:"
        for lang in "${failed_langs[@]}"; do
            echo "  - $lang (${LANG_NAMES[$lang]})"
        done
        exit 1
    fi

    if [[ $passed -gt 0 ]]; then
        echo ""
        echo "All sidecar tests passed!"
    fi
}

main "$@"
