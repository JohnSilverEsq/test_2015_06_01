function BlogApp() {
    var app = this;

    var loader_html = '<div class="modal fade" tabindex="-1" role="dialog" id="modalDialog">' +
        '<div class="modal-dialog"><div class="modal-content" id="modalContent">Loading...</div></div></div>';

    /*
     * Load the dialog's html from the server, bind the handler and show it.
     * @param url: dialog's page
     * @param data: data to pass to the server
     * @param handler: the model and event handler function
     * */
    function do_modal(url, data, handler) {
        // use the animation "loading" as a initial dialog's content
        var dlg = $(loader_html);
        // define the "shown" handler for the dialog
        dlg.on('shown.bs.modal', function () {
            // remember the current handler
            app.active_handler = handler;
            // define the request variable
            var req = null;
            // try to load the dialog's page
            $.ajax({
                url: url,
                type: 'GET',
                data: data,
                // in case of success:
                success: function (r) {
                    // get the dialog's content node
                    var content = document.getElementById('modalContent');
                    content.innerHTML = r['html'];
                    if (handler && handler.success)
                        handler.success(dlg, r['data']);
                },
                // in case of an error
                error: function (r, e) {
                    // if the loading was not aborted by user,
                    // replace the "loading" animation with the "ajax_error" message
                    if (e != 'abort') {
                        document.getElementById('modalContent').innerHTML =
                            '<div class="modal-body bg-danger" style="padding-top: 2em; padding-bottom: 2em;"><h2>Error loading dialog</h2></div>';
                    }
                },
                beforeSend: function (request) {
                    // remember the request to let user to cancel it
                    req = request;
                    // define the "Accept" header
                    req.setRequestHeader('Accept', 'application/json');
                },
                complete: function () {
                    // clear the request variable
                    req = null;
                }
            })
        }).on('hidden.bs.modal', function () {
            // forget the active handler
            delete (app.active_handler);
            // delete dialog's element from the document
            $('#modalDialog').remove();
        });

        // let's dance
        dlg.modal('show');
    }

    app.show_login_dialog = function () {
        do_modal('/login');
    };

    app.articles = ko.observableArray([]);

    app.loadArticles = function (url) {
        $.getJSON(url, {start_from: 0}, function (resp) {
            app.articles(resp && resp.data ? resp.data : []);
            ko.applyBindings(app.articles);
        });
    };

    app.delete_article = function (id) {
            $.ajax({
                url: '/article/' + id,
                type: 'DELETE',
                contentType: "application/json; charset=utf-8",
                dataType: "json",
                success: function (r) {
                    location.reload();
                },
                beforeSend: function (request) {
                    request.setRequestHeader('Accept', 'application/json');
                }
            });
    };

    app.edit_article = function (id) {
        function make_dict(sa)
        {
            res={};
            for (var i=0;i<sa.length;i++)
                    res[sa[i].name]=sa[i].value
            return res;
        }
        do_modal('/article', {id: id}, {
            on_ok: function () {
                $.ajax({
                    url: '/article/' + id,
                    type: 'PUT',
                    data: JSON.stringify(make_dict($('#active-form').serializeArray())),
                    contentType: "application/json; charset=utf-8",
                    dataType: "json",
                    success: function (r) {
                        location.reload();
                    },
                    beforeSend: function (request) {
                        request.setRequestHeader('Accept', 'application/json');
                    }
                });
            }
        });
    };
}

var app = new BlogApp();
