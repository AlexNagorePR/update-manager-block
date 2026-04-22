cmake_minimum_required(VERSION 3.8)
project(update_manager)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Install Python package
ament_python_install_package(${PROJECT_NAME})

ament_package()
