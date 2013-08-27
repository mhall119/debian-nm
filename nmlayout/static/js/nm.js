// Install fingerprint easy-copy-paste behaviour
$(function() {
    $("span.fpr").each(function(idx, el) {
        var el = $(el);
        var joined = $("<input>").attr("type", "text").attr("size", "40").val(el.text().replace(/ /g,""));
        el.after(joined);
        joined.hide();
        el.click(function(ev) {
            el.hide();
            joined.show();
            joined.focus();
        });
        joined.focusout(function(ev) {
            el.show();
            joined.hide();
        });
    });
});

function toggle_person_bio () {
    var personbios = $("td.personbio");
    var th_bio_a = personbios.parent('tr').children('th').children('a');
    if (th_bio_a.text() == "+") { th_bio_a.text("-"); } else { th_bio_a.text("+"); }
    personbios.toggle()
};

$(function () {
    $("td.personbio#collapsedbio").mouseover(function (ev) { toggle_person_bio(); });
});
