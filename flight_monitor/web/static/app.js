// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.flash-msg').forEach(function (el) {
    setTimeout(function () {
      var bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    }, 5000);
  });
});
