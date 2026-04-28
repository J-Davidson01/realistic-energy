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
)

target_include_directories(pipeline_e2e_c PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ../../workloads/c
)

find_package(PkgConfig REQUIRED)
pkg_check_modules(CJSON REQUIRED libcjson)

find_package(OpenSSL REQUIRED)

target_include_directories(pipeline_e2e_c PRIVATE ${CJSON_INCLUDE_DIRS})
target_link_directories(pipeline_e2e_c PRIVATE ${CJSON_LIBRARY_DIRS})

target_link_libraries(pipeline_e2e_c PRIVATE
    ${CJSON_LIBRARIES}
    OpenSSL::Crypto
)