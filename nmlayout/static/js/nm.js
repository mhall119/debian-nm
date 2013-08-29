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

$(function () {
    $("div.personbio").click(function (ev) {
        var el = $(this);
	el.find(".collapsed").toggle();
	el.find(".expanded").toggle();
    });
});
