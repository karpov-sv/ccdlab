Monitor = function(parent_id, base="/monitor", title="MONITOR"){
    this.base = base;
    this.title = title;

    this.last_status = {};

    var panel = $("<div/>", {class:"monitor panel panel-default"});

    var header = $("<div/>", {class:"panel-heading"}).appendTo(panel);
    var title = $("<h3/>", {class:"panel-title"}).html(title + " ").appendTo(header);
    this.throbber = $("<span/>", {class:"glyphicon glyphicon-refresh pull-right"}).appendTo(title);
    this.connstatus = $("<span/>", {class:"label label-default"}).appendTo(title);

    this.body = $("<div/>", {class:"panel-body"}).appendTo(panel);

    // this.misc = $("<div/>", {class:""}).appendTo($("<div/>").appendTo(this.body));

    // this.monitor_image = $("<img/>", {src:this.base + "/image.jpg", class:"image img-responsive center-block", style:"width:100%;max-width:512px;"}).appendTo(this.misc);
    // this.monitor_image.on('click', $.proxy(function(){
    //     if(this.monitor_image.css("max-width") == "512px"){
    //         this.monitor_image.css("width", "initial");
    //         this.monitor_image.css("max-width", "100%");
    //     } else {
    //         this.monitor_image.css("width", "100%");
    //         this.monitor_image.css("max-width", "512px");
    //     }
    // }, this));
    // new Updater(this.monitor_image, 1000);

    var list = $("<ul/>", {class:"list-group"}).appendTo(this.body);

    this.state = $("<li/>", {class:"list-group-item"}).appendTo(list);

    this.clients = $("<li/>", {class:"list-group-item"}).appendTo(list);

    this.cmdline = $("<input>", {type:"text", size:"40", class:"form-control"});

    $("<div/>", {class:"input-group"}).append($("<span/>", {class:"input-group-addon"}).html("Command:")).append(this.cmdline).appendTo(list);

    this.cmdline.pressEnter($.proxy(function(event){
        this.sendCommand(this.cmdline.val());
        event.preventDefault();
    }, this));

    var footer = $("<div/>", {class:"panel-footer"});//.appendTo(panel);

    var form = $("<form/>").appendTo(footer);
    // this.throbber = $("<span/>", {class:"glyphicon glyphicon-transfer"}).appendTo(form);
    this.delayValue = 2000;
    this.delay = $("<select/>", {id:getUUID()});
    $("<label>", {for: this.delay.get(0).id}).html("Refresh:").appendTo(form);
    $("<option>", {value: "1000"}).html("1").appendTo(this.delay);
    $("<option>", {value: "2000", selected:1}).html("2").appendTo(this.delay);
    $("<option>", {value: "5000"}).html("5").appendTo(this.delay);
    $("<option>", {value: "10000"}).html("10").appendTo(this.delay);
    this.delay.appendTo(form);
    this.delay.change($.proxy(function(event){
        this.delayValue = this.delay.val();
    }, this));

    panel.appendTo(parent_id);

    this.timer = 0;
    this.requestState();
}

Monitor.prototype.requestState = function(){
    $.ajax({
        url: this.base + "/status",
        dataType : "json",
        timeout : 1000,
        context: this,

        success: function(json){
            this.throbber.animate({opacity: 1.0}, 200).animate({opacity: 0.1}, 400);

            /* Crude hack to prevent jumping */
            st = document.body.scrollTop;
            sl = document.body.scrollLeft;
            this.updateStatus(json.status, json.clients);
            document.body.scrollTop = st;
            document.body.scrollLeft = sl;
        },

        complete: function( xhr, status ) {
            clearTimeout(this.timer);
            this.timer = setTimeout($.proxy(this.requestState, this), this.delayValue);
        }
    });
}

Monitor.prototype.updateStatus = function(status, clients){
    //this.status.html("");

    // status = json.status;
    // clients = json.clients;

    this.last_status = status;

    show(this.body);

    this.connstatus.html("Connected");
    this.connstatus.removeClass("label-danger").addClass("label-success");

    state = "Connections: " + label(status['nconnected']);
    cstate = "";

    state += " Clients:";

    for(var i=0; i < clients.length; i++){
        var client = clients[i]

        if(status[client['name']] == '0') {
            state += " " + label(client['name'], 'warning');
            cstate += label(client['name'], 'warning') + "<br>";
        } else {
            var s = status[client['name']];

            state += " " + label(client['name'], 'success');
            cstate += label(client['name'], 'success') + " :";

            for(var key in s){
                cstate += " " + key + ": " + label(s[key]);
            }

            cstate += "<br>";
        }
    }

    this.state.html(state);
    this.clients.html(cstate);
}

Monitor.prototype.sendCommand = function(command){
    $.ajax({
        url: this.base + "/command",
        data: {string: command}
    });
}

Monitor.prototype.makeButton = function(text, command, title)
{
    if(typeof(command) == "string")
        return $("<button>", {class:"btn btn-default", title:title}).html(text).click($.proxy(function(event){
            this.sendCommand(command);
            event.preventDefault();
        }, this));
    else if(typeof(command) == "function")
        return $("<button>", {class:"btn btn-default", title:title}).html(text).click($.proxy(command, this));
    else
        return $("<button>", {class:"btn btn-default disabled", title:title}).html(text);
}
