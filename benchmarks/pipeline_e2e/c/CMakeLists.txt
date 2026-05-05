cmake_minimum_required(VERSION 3.16)
project(pipeline_e2e C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(pipeline_e2e_c
    pipeline_e2e_main.c
    ../../workloads/c/pipeline_e2e_workload.c
    ../../workloads/c/json_parse_workload.c
    ../../workloads/c/sha256_workload.c
    ../../workloads/c/file_copy_workload.c
    ../../workloads/c/third_party/cjson/cJSON.c
)

target_include_directories(pipeline_e2e_c PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ../../workloads/c
    ../../workloads/c/third_party/cjson
)

find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

target_include_directories(pipeline_e2e_c PRIVATE
    ${OPENSSL_INCLUDE_DIR}
)

target_link_libraries(pipeline_e2e_c PRIVATE
    ${OPENSSL_CRYPTO_LIBRARY}
    Threads::Threads
    ${CMAKE_DL_LIBS}
)

target_compile_options(pipeline_e2e_c PRIVATE -O3 -march=native)