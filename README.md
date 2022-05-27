[![Build Status](http://runbot.odoo.com/runbot/badge/flat/1/8.0.svg)](http://runbot.odoo.com/runbot)
[![Tech Doc](http://img.shields.io/badge/8.0-docs-8f8f8f.svg?style=flat)](http://www.odoo.com/documentation/8.0) 
[![Help](http://img.shields.io/badge/8.0-help-8f8f8f.svg?style=flat)](https://www.odoo.com/forum/help-1)
[![Nightly Builds](http://img.shields.io/badge/8.0-nightly-8f8f8f.svg?style=flat)](http://nightly.odoo.com/)

Odoo
----

Odoo is a suite of web based open source business apps.

The main Odoo Apps include an <a href="https://www.odoo.com/page/crm">Open Source CRM</a>, <a href="https://www.odoo.com/page/website-builder">Website Builder</a>, <a href="https://www.odoo.com/page/e-commerce">eCommerce</a>, <a href="https://www.odoo.com/page/project-management">Project Management</a>, <a href="https://www.odoo.com/page/accounting">Billing &amp; Accounting</a>, <a href="https://www.odoo.com/page/point-of-sale">Point of Sale</a>, <a href="https://www.odoo.com/page/employees">Human Resources</a>, Marketing, Manufacturing, Purchase Management, ...  

Odoo Apps can be used as stand-alone applications, but they also integrate seamlessly so you get
a full-featured <a href="https://www.odoo.com">Open Source ERP</a> when you install several Apps.


Getting started with Odoo
-------------------------
For a standard installation please follow the <a href="https://www.odoo.com/documentation/8.0/setup/install.html">Setup instructions</a>
from the documentation.

If you are a developer you may type the following command at your terminal:

    wget -O- https://raw.githubusercontent.com/odoo/odoo/8.0/odoo.py | python

Then follow <a href="https://www.odoo.com/documentation/8.0/tutorials.html">the developer tutorials</a>


For Odoo employees
------------------

To add the odoo-dev remote use this command:

    $ ./odoo.py setup_git_dev

To fetch odoo merge pull requests refs use this command:

    $ ./odoo.py setup_git_review


Update Modules
--------------

The following command shows how to update all modules:

    $ ./odoo-bin update -dc ~/.local/etc/odoo.conf

With the parameter -dc you specify the configuration file

If you only want to update a specific module use:

    $ ./odoo-bin update -dc ~/.local/etc/odoo.conf --module=account


Module Repositories
-------------------

If you want to add additional module repositories, checkout your repository
at one directory up from the odoo source ../

The repository have to start with **addons-** . If it does, then all modules in this 
directory are auto detected. 

You only have to call the overall update described above, that the modules appear within the ui.