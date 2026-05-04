cmake_minimum_required(VERSION 3.16)
project(pipeline_e2e_stream C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(pipeline_e2e_stream_c
    pipeline_e2e_stream_main.c
    ../../workloads/c/pipeline_e2e_stream_workload.c
    ../../workloads/c/json_parse_workload.c
    ../../workloads/c/sha256_workload.c
    ../../workloads/c/file_copy_workload.c
    ../../workloads/c/third_party/cjson/cJSON.c
)

target_include_directories(pipeline_e2e_stream_c PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ../../workloads/c
    ../../workloads/c/third_party/cjson
)

find_package(OpenSSL REQUIRED)

target_link_libraries(pipeline_e2e_stream_c PRIVATE
    OpenSSL::Crypto
)

target_compile_options(pipeline_e2e_stream_c PRIVATE -O3 -march=native)