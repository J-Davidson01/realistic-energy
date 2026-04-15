cmake_minimum_required(VERSION 3.16)
project(file_copy C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(file_copy_c
    file_copy_main.c
    file_copy_workload.c
)

target_compile_options(file_copy_c PRIVATE -O3 -march=native)