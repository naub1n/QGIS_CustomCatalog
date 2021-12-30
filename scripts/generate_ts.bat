@echo off
call "C:\OSGeo4W64\bin\o4w_env.bat"
call "C:\OSGeo4W64\bin\qt5_env.bat"
call "C:\OSGeo4W64\bin\py3_env.bat"
pushd  %~dp0..\i18n

@echo on
pylupdate5 %cd%\custom_catalog.pro
popd