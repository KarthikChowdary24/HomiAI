const imageInput = document.getElementById("roomImage");

if (imageInput) {

    imageInput.addEventListener("change", function () {

        const file = this.files[0];

        if (file) {

            const preview = document.getElementById("preview");
            const status = document.getElementById("uploadStatus");

            preview.src = URL.createObjectURL(file);
            preview.style.display = "block";
            preview.style.animation = "fade .5s";

            if (status) {
                status.style.display = "block";
            }

        }

    });

}

const style = document.createElement("style");

style.innerHTML = `
@keyframes fade{

from{
opacity:0;
transform:scale(.9);
}

to{
opacity:1;
transform:scale(1);
}

}
`;

document.head.appendChild(style);