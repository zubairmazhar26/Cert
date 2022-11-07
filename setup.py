from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in cert/__init__.py
from cert import __version__ as version

setup(
	name="cert",
	version=version,
	description="Manage Cert App Related Customization",
	author="Bhavesh",
	author_email="iambhavesh95863@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
