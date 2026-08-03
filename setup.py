from setuptools import find_packages, setup

with open("requirements.txt") as f:
    install_requires = [x.strip() for x in f.read().split("\n") if x.strip() and not x.startswith("#")]

setup(
    name="growth_portal",
    version="0.1.0",
    description="Performance and growth intelligence for Justyol",
    author="Justyol",
    author_email="ahmedbadran2017@gmail.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
