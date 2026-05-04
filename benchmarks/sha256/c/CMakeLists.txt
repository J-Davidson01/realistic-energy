cmake_minimum_required(VERSION 3.16)
project(sha256_c C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

find_package(OpenSSL REQUIRED)

add_executable(sha256_c
    sha256_main.c
    ../../workloads/c/sha256_workload.c
)

target_include_directories(sha256_c PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

target_include_directories(sha256_c PRIVATE
    ${OPENSSL_INCLUDE_DIR}
)

target_link_libraries(sha256_c PRIVATE
    ${OPENSSL_CRYPTO_LIBRARY}
)
