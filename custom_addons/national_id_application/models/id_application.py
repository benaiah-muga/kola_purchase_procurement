from odoo import api, fields, models, _
from odoo.exceptions import UserError

class NationalIdApplication(models.Model):
    _name = 'national.id.application'
    _description = 'National ID Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    applicant_name = fields.Char(string='Applicant Name', required=True, tracking=True)
    date_of_birth = fields.Date(string='Date of Birth', required=True, tracking=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female')
    ], string='Gender', required=True, tracking=True)
    nin_number = fields.Char(string='NIN (Optional)', tracking=True)
    phone = fields.Char(string='Phone Number', tracking=True)
    email = fields.Char(string='Email Address', tracking=True)
    address = fields.Text(string='Physical Address', tracking=True)
    
    photo = fields.Binary(string='Applicant Photo', attachment=True)
    photo_filename = fields.Char(string='Photo Filename')
    
    lc_letter = fields.Binary(string='LC Reference Letter', attachment=True)
    lc_letter_filename = fields.Char(string='LC Letter Filename')
    
    partner_id = fields.Many2one('res.partner', string='Portal User', default=lambda self: self.env.user.partner_id)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('national.id.application') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})
        
    def action_review(self):
        self.write({'state': 'under_review'})
        
    def action_approve(self):
        self.write({'state': 'approved'})
        
    def action_reject(self):
        self.write({'state': 'rejected'})
