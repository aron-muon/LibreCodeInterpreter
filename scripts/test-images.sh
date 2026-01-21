#!/usr/bin/env bash
# Test code execution in all KubeCodeRun Docker images
# Works with DHI images that have no shell
#
# Usage: ./scripts/test-images.sh [OPTIONS]
#
# Options:
#   -t, --tag TAG        Image tag to test (default: latest)
#   -r, --registry REG   Registry prefix (e.g., aronmuon/kubecoderun)
#   -l, --language LANG  Test only specified language (can repeat)
#   -v, --verbose        Show full output from each test
#   -h, --help           Show this help message

set -euo pipefail

# Defaults
TAG="latest"
PREFIX="kcr"  # Local image prefix (matches build-images.sh)
REGISTRY=""   # When set, overrides PREFIX
VERBOSE=false
SPECIFIC_LANGS=()

# Expected output for all tests
EXPECTED_OUTPUT="Hello, KubeCodeRun!"

# Test code for each language
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

usage() {
    head -n 14 "$0" | tail -n 12 | sed 's/^# //'
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
            -l|--language)
                SPECIFIC_LANGS+=("$2")
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
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

# Run a stdin-based interpreted language test
# Usage: run_stdin_test <image> <entrypoint> <code> [args...]
run_stdin_test() {
    local image=$1
    local entrypoint=$2
    local code=$3
    shift 3
    local args=("$@")

    echo "$code" | docker run --rm -i \
        -w /mnt/data \
        --entrypoint "$entrypoint" \
        "$image" \
        "${args[@]}" 2>&1
}

# Run a compiled language test using bind mount
# Usage: run_compiled_test <image> <code> <filename> <compile_ep> <compile_args...> -- <run_ep> <run_args...>
run_compiled_test() {
    local image=$1
    local code=$2
    local filename=$3
    shift 3

    # Parse compile and run commands (separated by --)
    local compile_ep=$1
    shift
    local compile_args=()
    while [[ $# -gt 0 && $1 != "--" ]]; do
        compile_args+=("$1")
        shift
    done
    shift  # skip --

    local run_ep=$1
    shift
    local run_args=("$@")

    # Create temp directory for code (world-accessible for container's non-root user)
    local tmpdir
    tmpdir=$(mktemp -d)
    chmod 777 "$tmpdir"

    # Write code to file (world-readable)
    echo "$code" > "$tmpdir/$filename"
    chmod 644 "$tmpdir/$filename"

    # Compile
    docker run --rm \
        -v "$tmpdir:/mnt/data" \
        -w /mnt/data \
        --entrypoint "$compile_ep" \
        "$image" \
        "${compile_args[@]}" 2>&1

    # Run
    local output
    output=$(docker run --rm \
        -v "$tmpdir:/mnt/data" \
        -w /mnt/data \
        --entrypoint "$run_ep" \
        "$image" \
        "${run_args[@]}" 2>&1)

    # Cleanup
    rm -rf "$tmpdir"

    echo "$output"
}

# Run a single-command test with bind mount (for languages like Go that use 'go run')
# Usage: run_single_cmd_test <image> <code> <filename> <entrypoint> [args...]
run_single_cmd_test() {
    local image=$1
    local code=$2
    local filename=$3
    local entrypoint=$4
    shift 4
    local args=("$@")

    # Create temp directory (world-accessible for container's non-root user)
    local tmpdir
    tmpdir=$(mktemp -d)
    chmod 777 "$tmpdir"

    echo "$code" > "$tmpdir/$filename"
    chmod 644 "$tmpdir/$filename"

    local output
    output=$(docker run --rm \
        -v "$tmpdir:/mnt/data" \
        -w /mnt/data \
        --entrypoint "$entrypoint" \
        "$image" \
        "${args[@]}" 2>&1)

    rm -rf "$tmpdir"
    echo "$output"
}

# Run TypeScript test using ts-runner.js wrapper script
run_ts_test() {
    local image=$1
    local code=$2

    # Create temp directory (world-accessible for container's non-root user)
    local tmpdir
    tmpdir=$(mktemp -d)
    chmod 777 "$tmpdir"

    echo "$code" > "$tmpdir/code.ts"
    chmod 644 "$tmpdir/code.ts"

    local output
    # Need to set PATH explicitly since --entrypoint bypasses the image's ENTRYPOINT
    # which normally sets up the environment via env -i
    output=$(docker run --rm \
        -v "$tmpdir:/mnt/data" \
        -w /mnt/data \
        -e "PATH=/opt/node/bin:/usr/bin:/bin" \
        --entrypoint node \
        "$image" \
        /opt/scripts/ts-runner.js code.ts 2>&1)

    rm -rf "$tmpdir"
    echo "$output"
}

test_language() {
    local lang="$1"
    local name="${LANG_NAMES[$lang]}"
    local code="${TEST_CODE[$lang]}"
    local image_name="${LANG_IMAGE[$lang]}"

    local full_image
    full_image=$(get_full_image_name "$image_name")

    printf "%-12s %-20s " "[$lang]" "$name"

    # Check if image exists
    if ! docker image inspect "$full_image" &>/dev/null; then
        echo "SKIP (image not found: $full_image)"
        return 2
    fi

    local output
    local exit_code=0

    # Execute based on language type
    case $lang in
        # Stdin-based interpreted languages
        py)
            output=$(run_stdin_test "$full_image" python "$code" -) || exit_code=$?
            ;;
        js)
            output=$(run_stdin_test "$full_image" node "$code" -) || exit_code=$?
            ;;
        php)
            output=$(run_stdin_test "$full_image" php "$code") || exit_code=$?
            ;;
        r)
            output=$(run_stdin_test "$full_image" Rscript "$code" /dev/stdin) || exit_code=$?
            ;;

        # TypeScript uses wrapper script
        ts)
            output=$(run_ts_test "$full_image" "$code") || exit_code=$?
            ;;

        # Compiled languages
        go)
            # Use go run (single step) instead of build+run to avoid go.mod requirement
            output=$(run_single_cmd_test "$full_image" "$code" "code.go" \
                go run code.go) || exit_code=$?
            ;;
        java)
            output=$(run_compiled_test "$full_image" "$code" "Code.java" \
                javac Code.java -- java Code) || exit_code=$?
            ;;
        c)
            output=$(run_compiled_test "$full_image" "$code" "code.c" \
                gcc -o code code.c -- ./code) || exit_code=$?
            ;;
        cpp)
            output=$(run_compiled_test "$full_image" "$code" "code.cpp" \
                g++ -o code code.cpp -- ./code) || exit_code=$?
            ;;
        rs)
            output=$(run_compiled_test "$full_image" "$code" "code.rs" \
                rustc code.rs -o code -- ./code) || exit_code=$?
            ;;
        f90)
            output=$(run_compiled_test "$full_image" "$code" "code.f90" \
                gfortran -o code code.f90 -- ./code) || exit_code=$?
            ;;
        d)
            output=$(run_compiled_test "$full_image" "$code" "code.d" \
                ldc2 code.d -of=code -- ./code) || exit_code=$?
            ;;
        *)
            echo "SKIP (no test configured)"
            return 2
            ;;
    esac

    # Normalize output (trim whitespace, handle Fortran's leading space)
    local normalized_output
    normalized_output=$(echo "$output" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | head -1)

    if [[ $exit_code -ne 0 ]]; then
        echo "FAIL (exit code: $exit_code)"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Output: $output"
        fi
        return 1
    elif [[ "$normalized_output" != "$EXPECTED_OUTPUT" ]]; then
        echo "FAIL (output mismatch)"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Expected: '$EXPECTED_OUTPUT'"
            echo "  Got:      '$normalized_output'"
        fi
        return 1
    else
        echo "PASS"
        if [[ "$VERBOSE" == true ]]; then
            echo "  Output: $normalized_output"
        fi
        return 0
    fi
}

main() {
    parse_args "$@"

    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║          KubeCodeRun Docker Image Tester                 ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  Tag:      ${TAG}"
    if [[ -n "$REGISTRY" ]]; then
        echo "║  Registry: ${REGISTRY}"
    fi
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""

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

    echo "Running tests..."
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
        echo "All tested images executed code successfully!"
    fi
}

main "$@"
