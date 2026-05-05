cmake_minimum_required(VERSION 3.16)
project(json_parse C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(json_parse_c
    json_parse_main.c
    ../../workloads/c/json_parse_workload.c
    ../../workloads/c/json_parse_workload_yyjson.c
    ../../workloads/c/third_party/cjson/cJSON.c
    ../../workloads/c/third_party/yyjson/yyjson.c
)

target_include_directories(json_parse_c PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ../../workloads/c
    ../../workloads/c/third_party/cjson
    ../../workloads/c/third_party/yyjson
)

target_compile_options(json_parse_c PRIVATE -O3 -march=native)
