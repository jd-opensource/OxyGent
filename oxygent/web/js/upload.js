function uploadFile(file, callback) {
    console.log(file);
    const formData = new FormData();
    formData.append('file', file);

    fetch('../upload', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            callback(data)
            // document.getElementById('result').textContent = '上传成功: ' + JSON.stringify(data);
        })
        .catch(error => {
            console.log(error);
            // document.getElementById('result').textContent = '上传失败: ' + error;
        });
}