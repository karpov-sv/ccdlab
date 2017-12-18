Monitor = function(parent_id, base="/monitor", title="Monitor"){
    this.base = base;
    this.title = title;
    this.last_status = {};
    this.parent_id = parent_id;
    this.clients = [];

    // Render the main block from the template
    var template = getData("/template/monitor.html");
    var rendered = $.templates(template).render(this);
    this.id = $(this.parent_id).html(rendered);

    // Command line
    this.cmdline = $(this.id).find(".monitor-cmdline");
    this.cmdline.pressEnter($.proxy(function(event){
        this.sendCommand(this.cmdline.val());
        event.preventDefault();
    }, this));

    //
    this.timer = 0;
    this.refreshDelay = 2000;
    this.requestState();
}

// Synchronously request data from server and return it
getData = function(url){
    var result = "";

    $.ajax({
        url: url,
        async: false,
        context: this,
        dataType: "text",
        success: function(text){
            result = text;
        }
    });

    return result;
}

Monitor.prototype.sendCommand = function(command){
    $.ajax({
        url: this.base + "/command",
        data: {string: command}
    });
}

Monitor.prototype.requestState = function(){
    $.ajax({
        url: this.base + "/status",
        dataType : "json",
        timeout : 1000,
        context: this,

        success: function(json){
            $(this.id).find('.monitor-throbber').animate({opacity: 1.0}, 200).animate({opacity: 0.1}, 400);

            this.json = json;

            // Crude hack to prevent jumping
            st = document.body.scrollTop;
            sl = document.body.scrollLeft;
            this.updateStatus(json.status, json.clients);
            document.body.scrollTop = st;
            document.body.scrollLeft = sl;
        },

        error: function(){
            $(this.id).find(".monitor-connstatus").html("Disconnected").addClass("label-danger").removeClass("label-success");
            $(this.id).find(".monitor-body").addClass("disabled-controls");
        },

        complete: function(xhr, status) {
            clearTimeout(this.timer);
            this.timer = setTimeout($.proxy(this.requestState, this), this.refreshDelay);
        }
    });
}

Monitor.prototype.updateStatus = function(status, clients){
    show($(this.id).find(".monitor-body"));
    enable($(this.id).find(".monitor-body"));

    $(this.id).find(".monitor-connstatus").html("Connected").removeClass("label-danger").addClass("label-success");
    $(this.id).find(".monitor-body").removeClass("disabled-controls");

    if(this.clients.length != Object.keys(clients).length){
        this.makeClients(clients, status);
    }

    for(var i=0; i < this.clients.length; i++){
        var client = clients[this.clients[i].name];
        var client_status = status[client['name']];
        var widget = this.clients[i]['widget'];

        if(client_status == '0') {
            this.clients[i]['state'].removeClass("label-success").addClass("label-warning");

            hide(widget.find(".monitor-client-body"));
            hide(widget.find(".monitor-client-hwstatus"));
            widget.find(".monitor-client-connstatus").html("Disconnected").removeClass("label-success").addClass("label-danger");
        } else {
            this.clients[i]['state'].addClass("label-success").removeClass("label-warning");

            show(widget.find(".monitor-client-body"));
            show(widget.find(".monitor-client-hwstatus"));
            widget.find(".monitor-client-connstatus").html("Connected").addClass("label-success").removeClass("label-danger");

            if(client_status['progress'] && client_status['progress'] > 0){
                show(widget.find(".monitor-client-progressdiv"));

                widget.find(".monitor-client-progress").clients[i].progress.css("width", 100*client_status['progress']+"%");
            } else {
                hide(widget.find(".monitor-client-progressdiv"));
            }

            if(client_status['hw_connected'] == '1'){
                widget.find(".monitor-client-hwstatus").html("HW connected").removeClass("label-danger").addClass("label-success");
            } else {
                widget.find(".monitor-client-hwstatus").html("HW disconnected").removeClass("label-success").addClass("label-danger");
            }

            // Remove entries no more in status
            for(var name in this.clients[i]['status']){
                if(!(name in client_status))
                    $.observable(this.clients[i]['status']).removeProperty(name);
            }

            // Update tempated view using data-linked values
            $.observable(this.clients[i]['status']).setProperty(client_status);
        }
    }

    this.last_status = status;
}

Monitor.prototype.makeClients = function(clients, status)
{
    var clientsdiv = $(this.id).find('.monitor-clients');
    var clientsstate = $(this.id).find('.monitor-clients-state');

    clientsdiv.html("");
    clientsstate.html("");

    this.clients = [];

    for(var name in clients){
        var client = {'name':name, 'params':clients[name]};

        this.clients.push(client);

        client['state'] = $("<span/>", {class:"monitor-client-state label label-default", style:'margin-right: 0.5em'}).html(name).appendTo(clientsstate);

        client['template'] = getData('/template/' + clients[name]['template']);
        client['widget'] = $("<div/>").appendTo($(this.id).find('.monitor-clients'));
        client['status'] = status[name];

        // Render the template with data-linking to client object
        $.templates(client['template']).link(client['widget'], client);

        // Create updaters to refresh the plots
        for(var name in client['params']['plots']){
            new Updater(client['widget'].find('.monitor-plot-'+client['name']+'-'+name), 10000);
        }
    }
}
