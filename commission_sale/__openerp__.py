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
    "name": "oerp.at Sale Commission",
    "description": """
Commission based on Sale
========================

* creates commission based on sales
* creates commission based on contracts

""",
    "version": "1.0",
    "author": "oerp.at",
    "category": "Commission",
    "depends": [
        "at_base",
        "at_sale",
        "at_account",
        "commission",
        "sales_team",
        "product",
        "account",
    ],
    "data": [
        "security.xml",
        "data/analytic_journals.xml",
        "data/products.xml",
        "data/properties.xml",
        "view/pricelist_item_view.xml",
        "view/crm_section_view.xml",
        "view/bonus_view.xml",
        "view/product_view.xml",
        "view/sale_view.xml",
        "view/invoice_view.xml",
        "report/sale_commission_report.xml",
    ],
    "auto_install": False,
    "installable": True,
}
