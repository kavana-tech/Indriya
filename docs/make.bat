@ECHO OFF
pushd %~dp0

REM Minimal Sphinx batch wrapper for Windows.

set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "" goto help

if "%1" == "clean" (
    rmdir /s /q "%BUILDDIR%" 2>nul
    goto end
)

%SPHINXBUILD% -M %1 "%SOURCEDIR%" "%BUILDDIR%"
goto end

:help
%SPHINXBUILD% -M help "%SOURCEDIR%" "%BUILDDIR%"

:end
popd
