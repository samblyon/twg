$(function(){
    $('#btnSignUp').click(function(){
        
        $.ajax({
            url: '/signUp',
            data: $('form').serialize(),
            type: 'POST',
            success: function(response){
                console.log(response);
                var text = new String(response);
                
                if (text.indexOf("successfully") > -1) {
                    alert("Annnd... you're in!");
                window.location.href = "/showSignin";
                }
            },
            error: function(error){
                console.log(error);
            }
        });

       
    });

});

