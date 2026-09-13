from setuptools import find_packages, setup

package_name = 'limo_dashboard'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/dashboard.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jaeho',
    maintainer_email='woghjaeho1@gmail.com',
    description='Single-window Qt dashboard for the LIMO sim.',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'dashboard_node = limo_dashboard.dashboard_node:main',
        ],
    },
)
