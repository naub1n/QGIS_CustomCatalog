@echo off
call "C:\OSGeo4W64\bin\o4w_env.bat"
pushd  %~dp0..\i18n

@echo on
python3 "%PYTHONHOME%\Scripts\pylupdate5.exe" %cd%\custom_catalog.pro
popd