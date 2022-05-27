# -*- coding: utf-8 -*-
# -*- encoding: utf-8 -*-

#############################################################################
#
#    Copyright (c) 2007 Martin Reisenhofer <martin.reisenhofer@funkring.net>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    "name": "oerp.at Project",
    "description": """
Project Extensions
==================

Additional project based functions and utilities for dependent
modules

""",
    "version": "1.0",
    "author": "funkring.net",
    "website": "http://www.funkring.net",
    "category": "Project Management",
    "depends": ["project", "at_base", "project_issue"],
    "data": [
        "view/project_view.xml",
        "view/task_division_view.xml",
        "report/project_issue_report.xml",
        "report/task_report.xml",
        "report/task_list_report.xml",
        "report/ticket_list_report.xml",
        "security.xml",
    ],
    "auto_install": False,
    "installable": True,
}
