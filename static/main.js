function stringToHTML(text) {
	return new DOMParser().parseFromString(text, "text/html").body.firstChild;
}
function removePopup() {
	document.querySelector(".popup").remove();
	document.querySelector(".popup-background").remove();
}
function Popup(popup) {
	popup.classList.add("popup");
	let back = document.createElement("div");
	back.className = "popup-background";
	back.onclick = () => removePopup();
	
	document.body.appendChild(back);
	document.body.appendChild(popup);
}
function togglePasswords() {
	for (let pass of [
		...document.getElementsByName("pass"),
		 ...document.getElementsByName("pass_repeat"),
	])
		pass.type = pass.type == "text" ? "password" : "text";
} 
