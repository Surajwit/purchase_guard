frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {
        if (!frm.fields_dict.purchase_guard_summary) return;
        if (frm.doc.docstatus !== 1) {
            frm.toggle_display("purchase_guard_section", false);
            return;
        }
        frm.toggle_display("purchase_guard_section", true);
        load_invoice_guard(frm);
        frm.add_custom_button(__("Run Purchase Guard Scan"), function() {
            frappe.call({method:"purchase_guard.purchase_guard.api.scan_invoice",args:{invoice:frm.doc.name},freeze:true,freeze_message:__("Analyzing purchase risk...")}).then(function(r){
                frappe.show_alert({message:__("{0} finding(s) created",[r.message || 0]),indicator:"blue"});
                load_invoice_guard(frm);
            });
        }, __("Purchase Guard"));
    }
});
function load_invoice_guard(frm){
    frappe.call({method:"purchase_guard.purchase_guard.api.get_invoice_guard",args:{invoice:frm.doc.name}}).then(function(r){
        var rows=r.message||[]; var el=frm.fields_dict.purchase_guard_summary.$wrapper;
        if(!rows.length){el.html('<div class="pg-form-empty">✓ No Purchase Guard findings for this invoice.</div>');return;}
        var score=Math.max.apply(null,rows.map(function(x){return Number(x.risk_score||0);}));
        var html='<div class="pg-form-guard"><div class="pg-form-score"><div><div class="pg-eyebrow">PURCHASE GUARD</div><h3>'+ (score>=80?'HIGH RISK':score>=50?'REVIEW REQUIRED':'MONITOR') +'</h3><p>'+rows.length+' issue(s) detected</p></div><span class="pg-pill '+(score>=80?'critical':score>=50?'high':'medium')+'">'+score+'/100</span></div>';
        rows.forEach(function(x){html+='<div class="pg-form-finding"><div><strong>'+frappe.utils.escape_html(x.title)+'</strong><div class="pg-muted">'+frappe.utils.escape_html(x.evidence)+'</div></div><span class="pg-pill '+(Number(x.risk_score)>=80?'critical':Number(x.risk_score)>=50?'high':'medium')+'">'+x.severity+'</span></div>';});
        html+='</div>';el.html(html);
    });
}
