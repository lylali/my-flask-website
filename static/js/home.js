
/*
  The following JavaScript codes are adapted from the "home.js" file created by Rish Bhardwaj.
  Original source: https://github.com/crearo/portfolio/blob/main/static/js/home.js
*/

$(function() {
  $(".typed").typed({
    strings: [
      "welcome!<br/>" +
      "><span class='caret'>$</span> education: MSc in Computing at Cardiff University<br/> ^300" +
      "><span class='caret'>$</span> skills: Python, Flask, Jinja, JavaScript, HTML, CSS<br/> ^300" +
      "><span class='caret'>$</span> hobbies: hiking, writing, films, games<br/> ^300" +
      "><span class='caret'>$</span> location: United Kingdom<br/> ^300" +
      "><span class='caret'>$</span> looking for: placement year or graduate jobs<br/> ^300"
    ],
    showCursor: true,
    cursorChar: '_',
    autoInsertCss: true,
    typeSpeed: 0.001,
    startDelay: 50,
    loop: false,
    showCursor: false,
    onStart: $('.message form').hide(),
    onStop: $('.message form').show(),
    onTypingResumed: $('.message form').hide(),
    onTypingPaused: $('.message form').show(),
    onComplete: $('.message form').show(),
    onStringTyped: function(pos, self) {$('.message form').show();},
  });
  $('.message form').hide()
});
