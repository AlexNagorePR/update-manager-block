from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'update_manager'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['tests']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name,
         ['package.xml']),
    ],
    install_requires=[
        'setuptools',
        'lockfile',
    ],
    zip_safe=True,
    author='Balena',
    author_email='support@balena.io',
    maintainer='Balena',
    maintainer_email='support@balena.io',
    keywords=['ROS2'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Topic :: Software Development',
    ],
    description='Update manager for Balena/ROS2',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'main = update_manager.main:main',
        ],
    },
)