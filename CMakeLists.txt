cmake_minimum_required(VERSION 3.8)
project(update_manager)

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Generate service interfaces
rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/GetUpdateState.srv"
)

# Install Python modules
ament_python_install_package(update_manager)

# Install Python executables
install(PROGRAMS
  main.py
  DESTINATION lib/${PROJECT_NAME}
)

# Make sure that the build depends on the generated files
ament_package()
