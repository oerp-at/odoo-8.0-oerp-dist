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

from openerp import models, fields, api, _

class res_partner(models.Model):
    _inherit = "res.partner"
    
    district_id = fields.Many2one("district.district", "District", index=True)
    
    @api.multi
    def onchange_district(self, district_id):
        if district_id:
            district = self.env["district.district"].browse(district_id)
            value =  {}
            res = {"value" : value}
            if district.country_id:
                value["country_id"] = district.country_id
            if district.state_id:
                value["state_id"] = district.state_id
            return res
        return {}
