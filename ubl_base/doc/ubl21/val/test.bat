@echo off
call validate ..\xsd\maindoc\UBL-Order-2.1.xsd order-test-good.xml
call validate ..\xsd\maindoc\UBL-Order-2.1.xsd order-test-bad1.xml
call validate ..\xsd\maindoc\UBL-Order-2.1.xsd order-test-bad2.xml
