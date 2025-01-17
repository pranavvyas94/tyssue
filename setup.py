import os
import re
import sys
import platform
import subprocess
import warnings

from distutils.version import LooseVersion
from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext


DISTNAME = "tyssue"
DESCRIPTION = "tyssue is a living tissues, cell level, modeling library"
LONG_DESCRIPTION = (
    "tyssue uses the scientific python ecosystem to model"
    " epithelium at the cellular level"
)
MAINTAINER = "Guillaume Gay"
MAINTAINER_EMAIL = "guillaume@damcb.com"
URL = "https://github.com/DamCB/tyssue"
LICENSE = "GPL-3.0"
DOWNLOAD_URL = "https://github.com/DamCB/tyssue.git"

files = ["*.so*", "*.a*", "*.lib*", "config/*/*.json", "stores/*.*"]


## Version management copied form numpy
## Thanks to them!
MAJOR = 0
MINOR = 5
MICRO = 0
ISRELEASED = False
VERSION = "%d.%d.%s" % (MAJOR, MINOR, MICRO)


def git_version():
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ["SYSTEMROOT", "PATH"]:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env["LANGUAGE"] = "C"
        env["LANG"] = "C"
        env["LC_ALL"] = "C"
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(["git", "rev-parse", "HEAD"])
        GIT_REVISION = out.strip().decode("ascii")
    except OSError:
        GIT_REVISION = "Unknown"

    return GIT_REVISION


def get_version_info():
    # Adding the git rev number needs to be done inside write_version_py(),
    # otherwise the import of tyssue.version messes up the build under Python 3.
    FULLVERSION = VERSION
    if os.path.exists(".git"):
        GIT_REVISION = git_version()
    elif os.path.exists("tyssue/version.py"):
        # must be a source distribution, use existing version file
        # read from it instead of importing to avoid importing
        # the whole package
        with open("tyssue/version.py", "r") as fh:
            for line in fh.readlines():
                if line.startswith("git_revision"):
                    GIT_REVISION = line.split("=")[-1][2:-2]
                    break
            else:
                GIT_REVISION = "Unknown"
    else:
        GIT_REVISION = "Unknown"

    if not ISRELEASED:
        FULLVERSION += ".dev0+" + GIT_REVISION[:7]

    return FULLVERSION, GIT_REVISION


def write_version_py(filename="tyssue/version.py"):
    cnt = """
# THIS FILE IS GENERATED FROM tyssue SETUP.PY
#
short_version = '%(version)s'
version = '%(version)s'
full_version = '%(full_version)s'
git_revision = '%(git_revision)s'
release = %(isrelease)s
if not release:
    version = full_version
"""
    FULLVERSION, GIT_REVISION = get_version_info()

    a = open(filename, "w")
    try:
        a.write(
            cnt
            % {
                "version": VERSION,
                "full_version": FULLVERSION,
                "git_revision": GIT_REVISION,
                "isrelease": str(ISRELEASED),
            }
        )
    finally:
        a.close()


## Extension management from pybind/cmake_example
class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def run(self):
        try:
            out = subprocess.check_output(["cmake", "--version"])
        except OSError:
            warnings.warn(
                "CMake must be installed to build the following extensions: "
                + ", ".join(e.name for e in self.extensions)
            )
            return
        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        cmake_args = [
            "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=" + extdir,
            "-DPYTHON_EXECUTABLE=" + sys.executable,
        ]

        cfg = "Debug" if self.debug else "Release"
        build_args = ["--config", cfg]

        if platform.system() == "Windows":
            cmake_args += [
                "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}".format(cfg.upper(), extdir)
            ]
            if sys.maxsize > 2 ** 32:
                cmake_args += ["-A", "x64"]
            build_args += ["--", "/m"]
        else:
            cmake_args += ["-DCMAKE_BUILD_TYPE=" + cfg]
            build_args += ["--", "-j2"]

        env = os.environ.copy()
        env["CXXFLAGS"] = '{} -DVERSION_INFO=\\"{}\\"'.format(
            env.get("CXXFLAGS", ""), self.distribution.get_version()
        )
        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)
        subprocess.check_call(
            ["cmake", ext.sourcedir] + cmake_args, cwd=self.build_temp, env=env
        )
        subprocess.check_call(
            ["cmake", "--build", "."] + build_args, cwd=self.build_temp
        )
        print(env["CXXFLAGS"])
        print()  # Add an empty line for cleaner output


if __name__ == "__main__":

    write_version_py()
    setup(
        name=DISTNAME,
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        maintainer=MAINTAINER,
        maintainer_email=MAINTAINER_EMAIL,
        url=URL,
        license=LICENSE,
        download_url=DOWNLOAD_URL,
        version=VERSION,
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved :: MPL v2.0",
            "Natural Language :: English",
            "Operating System :: MacOS",
            "Operating System :: Microsoft",
            "Operating System :: POSIX :: Linux",
            "Programming Language :: Python :: 3.6",
            #                     "Programming Language :: Python :: Implementation :: CPython",
            "Topic :: Scientific/Engineering :: Bio-Informatics",
            "Topic :: Scientific/Engineering :: Medical Science Apps",
        ],
        packages=find_packages(),
        package_data={"tyssue": files},
        include_package_data=True,
        ext_modules=[CMakeExtension("tyssue/collisions/cpp/c_collisions")],
        cmdclass=dict(build_ext=CMakeBuild),
        zip_safe=False,
    )
