function alert_notify(class_type, msgHeader, msgValue ){
    alert_html = '<div class="mt-2 alert '+ class_type +' alert-dismissible fade show" role="alert"> \
    <strong>'+msgHeader+'</strong> '+msgValue+' \
    <button type="button" class="close" data-dismiss="alert" aria-label="Close"> \
    <span aria-hidden="true">&times;</span></button></div>';

    $(alert_html).insertBefore('#alert-base').delay(3000)
    .fadeOut(function() {
       $(this).remove(); 
    });

}

