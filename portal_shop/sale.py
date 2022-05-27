# -*- coding: utf-8 -*-
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

from openerp.osv import fields, osv


class sale_order(osv.Model):
    _inherit = "sale.order"

    def _writeable(self, cr, uid, ids, field_name, arg, context=None):
        writable = self.check_access_rights(cr, uid, "write", raise_exception=False)
        res = dict.fromkeys(ids, writable)
        return res

    _columns = {
        "writeable": fields.function(
            _writeable, string="Writeable", type="boolean", store=False
        )
    }
