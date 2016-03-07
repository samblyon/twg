$(function(){
    $('#btnSignUp').click(function(){
        
        $.ajax({
            url: '/signUp',
            data: $('form').serialize(),
            type: 'POST',
            success: function(response){
                console.log(response);
                console.log(typeof response);
                var text = new String(response);
                
                if (text.indexOf("successfully") > -1) {
                    alert("Annnd... you're in!");
                    // console.log("poop!");
                window.location.href = "/showSignin";
                }
            },
            error: function(error){
                console.log(error);
            }
        });

       
    });

});

