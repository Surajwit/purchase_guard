frappe.ui.form.on("Supplier", {
    refresh(frm) {
        if (!frm.fields_dict.purchase_guard_supplier_summary) return;
        load_supplier_guard(frm);
        if (!frm.is_new()) frm.add_custom_button(__("Purchase Guard"), function(){ load_supplier_guard(frm); }, __("Actions"));
    }
});
function load_supplier_guard(frm){
    if(frm.is_new()) return;
    frappe.call({method:"purchase_guard.api.get_supplier_guard",args:{supplier:frm.doc.name}}).then(function(r){
        var d=r.message||{},a=d.assessment,alerts=d.alerts||[],el=frm.fields_dict.purchase_guard_supplier_summary.$wrapper;
        if(!a){el.html('<div class="pg-form-empty">No Purchase Guard assessment yet.</div>');return;}
        var score=Number(a.risk_score||0);var html='<div class="pg-form-guard"><div class="pg-form-score"><div><div class="pg-eyebrow">PURCHASE GUARD</div><h3>Supplier Health</h3><p>'+frappe.utils.escape_html(a.risk_level||'')+' risk · '+alerts.length+' open alert(s)</p></div><span class="pg-pill '+(score>=80?'critical':score>=50?'high':score>=25?'medium':'low')+'">'+score+'/100</span></div><div class="pg-metrics">'+metric('Price Competitiveness',a.price_competitiveness_score)+metric('Invoice Accuracy',a.invoice_accuracy_score)+metric('Delivery Performance',a.delivery_performance_score)+metric('Payment Behaviour',a.payment_behavior_score)+'</div><div class="pg-muted">Purchase spend: ₹'+Number(a.purchase_spend||0).toLocaleString('en-IN')+' · Concentration: '+Number(a.supplier_concentration_pct||0).toFixed(1)+'%</div></div>';el.html(html);
    });
}
function metric(label,value){return '<div class="pg-metric"><span>'+label+'</span><strong>'+Number(value||0)+'/100</strong></div>';}
