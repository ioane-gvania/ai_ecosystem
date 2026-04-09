document.getElementById('markdown-input').addEventListener('input', function(e) {
    fetch('/api/preview', {method: 'POST', body: this.value})
        .then(response => response.text())
        .then(data => document.getElementById('preview').innerHTML = data);
});
