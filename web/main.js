$(document).ready(function(){
    path = window.location.pathname;

    monitor = new Monitor("#contents-wide");
    document.title = "Monitor";

    // Stuff for JsRender/JsViews
    $.views.settings.allowCode(true);

    $.views.helpers({
        list: function(...a) {return a;}
    });

    $.views.tags({
        status: function(name) {
            return '<span class="label label-primary" style="margin-right: 1em" data-link="~root.status.' + name + '"> - </span>';
        }
    });
});
