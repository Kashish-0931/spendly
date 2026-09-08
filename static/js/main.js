// main.js — students will add JavaScript here as features are built

// Confirm prompt for destructive actions. Any submit button (or form) carrying a
// data-confirm attribute asks the user before the form is sent. Progressive
// enhancement only — the server still enforces ownership if JS is disabled.
document.addEventListener("submit", function (event) {
    var form = event.target;
    var source = event.submitter || form;
    var message = source.getAttribute("data-confirm") || form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
        event.preventDefault();
    }
});
