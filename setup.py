from glob import glob
from setuptools import setup

package_name = 'pai2_final'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/data', glob('data/*.json')),
        ('share/' + package_name + '/web', glob('web/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pai2_final maintainer',
    maintainer_email='noreply@example.com',
    description='Offline-friendly quiz chatbot with CRANE+ V2 Gazebo reactions',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'pai2_final_quiz = pai2_final.pai2_final_quiz:main',
            'pai2_final_motion = pai2_final.pai2_final_motion:main',
            'pai2_final_web = pai2_final.pai2_final_web:main',
        ],
    },
)
