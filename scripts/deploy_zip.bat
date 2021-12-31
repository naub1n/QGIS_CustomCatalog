@echo off
call "C:\OSGeo4W64\bin\o4w_env.bat"
PATH C:\Progra~1\7-Zip;%PATH%
pushd  %~dp0..

@echo on
pb_tool zip
popd