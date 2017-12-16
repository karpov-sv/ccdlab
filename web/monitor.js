Monitor = function(parent_id, base="/monitor", title="Monitor"){
    this.base = base;
    this.title = title;

    this.last_status = {};

    var panel = $("<div/>", {class:"monitor panel panel-default"});

    var header = $("<div/>", {class:"panel-heading"}).appendTo(panel);
    var title = $("<h3/>", {class:"panel-title"}).html(title + " ").appendTo(header);
    this.throbber = $("<span/>", {class:"glyphicon glyphicon-refresh pull-right"}).appendTo(title);
    this.connstatus = $("<span/>", {class:"label label-default"}).appendTo(title);
        
    this.body = $("<div/>", {class:"panel-body"}).appendTo(panel);

    var list = $("<ul/>", {class:"list-group"}).appendTo(this.body);

    this.state = $("<li/>", {class:"list-group-item"}).appendTo(list);

    this.cmdline = $("<input>", {type:"text", size:"40", class:"form-control"});
    this.cmdtarget = $("<select/>", {class:"selectpicker input-group-btn"});

    $("<div/>", {class:"input-group"}).append($("<span/>", {class:"input-group-addon"}).html("Command:")).append(this.cmdline).appendTo(list);

    this.cmdline.pressEnter($.proxy(function(event){
        this.sendCommand(this.cmdline.val());
        event.preventDefault();
    }, this));

    this.clientsdiv = $("<div/>").appendTo(this.body);
    this.clients = [];

    var footer = $("<div/>", {class:"panel-footer"});//.appendTo(panel);

    var form = $("<form/>").appendTo(footer);
    this.delayValue = 2000;

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

            this.json = json;
            
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
    this.last_status = status;

    show(this.body);

    this.connstatus.html("Connected");
    this.connstatus.removeClass("label-danger").addClass("label-success");

    if(this.clients.length != Object.keys(clients).length){
        this.makeClients(clients);
    }

    state = "";
    //state += "Connections: " + label(status['nconnected']);
    state += " Clients:";

    for(var i=0; i < this.clients.length; i++){
        var client = clients[this.clients[i].name];
        var client_status = status[client['name']];
        var html = "";

        if(client_status == '0') {
            state += " " + label(client['name'], 'warning');

            hide(this.clients[i].body);
            this.clients[i].connstatus.html("Disconnected");
            this.clients[i].connstatus.removeClass("label-success").addClass("label-danger");
        } else {
            state += " " + label(client['name'], 'success');

            show(this.clients[i].body);
            this.clients[i].connstatus.html("Connected");
            this.clients[i].connstatus.removeClass("label-danger").addClass("label-success");

            if(client_status['progress'] && client_status['progress'] > 0){
                show(this.clients[i].progressdiv);

                this.clients[i].progress.css("width", 100*client_status['progress']+"%");
            } else {
                hide(this.clients[i].progressdiv);
            }

            if(client_status['hw_connected'] == '1'){
                this.clients[i].hwstatus.html("HW connected");
                this.clients[i].hwstatus.removeClass("label-danger").addClass("label-success");                
            } else {
                this.clients[i].hwstatus.html("HW disconnected");
                this.clients[i].hwstatus.removeClass("label-success").addClass("label-danger");   
            }
            
            for(var key in client_status){
                html += key + ": " + label(client_status[key]) + " ";
            }
        }

        this.clients[i].state.html(html);
    }

    this.state.html(state);
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

Monitor.prototype.makeClients = function(clients)
{
    this.clientsdiv.html("");
    this.clients = [];
    
    for(var name in clients){
        client = {'name':name};
        
        var div = $("<div/>", {class:"panel panel-default"}).appendTo(this.clientsdiv);
        var header = $("<div/>", {class:"panel-heading"}).appendTo(div);
        var title = $("<h3/>", {class:"panel-title"}).appendTo(header);
        client.title = $("<span/>", {style:"margin-right: 0.5em"}).html(clients[name]['name']).appendTo(title);
        client.connstatus = $("<span/>", {class:"label label-default", style:"margin-right: 0.5em"}).appendTo(title);
        client.hwstatus = $("<span/>", {class:"label label-default", style:"margin-right: 0.5em"}).appendTo(title);
        var body = $("<div/>", {class:"panel-body", style:"padding: 1px; margin: 1px"}).appendTo(div);
        client.body = body;
        
        client.progressdiv = $("<div/>", {class:"progress", style:"margin: 0; padding: 0"}).appendTo(body);
        client.progress = $("<div/>", {class:"progress-bar", style:"width: 0%"}).appendTo(client.progressdiv);

        client.state = $("<div/>", {class: "", style:"padding: 5px"}).appendTo(body);

        if(clients[name]['description'])
            client.title.html(clients[name]['description']);

        this.clients.push(client);
    }
}
