// console.log("WELCOME TO SPOTIFY");

// let songsLoaded = false;
// let currentAudio = null;

// // Load the list of songs from the server
// async function getSongs() {
//     let fet = await fetch("http://127.0.0.1:5500/Spotify/songs/");
//     let response = await fet.text();

//     let div = document.createElement("div");
//     div.innerHTML = response;

//     let a = div.getElementsByTagName("a");
//     let songs = [];

//     for (let index = 0; index < a.length; index++) {
//         const element = a[index];
//         if (element.href.endsWith(".mp3")) {
//             songs.push(element.href.split("/songs/")[1]);
//         }
//     }

//     return songs; // list of songs
// }

// // Called when Play button is clicked
// async function main() {
//     // If audio is already playing, do nothing
//     if (currentAudio && !currentAudio.paused) {
//         return;
//     }

//     const playsong = await getSongs();

//     // Play only the first song
//     if (!currentAudio) {
//         currentAudio = new Audio(`songs/${playsong[1]}`);
//     }
//     currentAudio.play();

//     // Only load song list once
//     if (!songsLoaded) {
//         const songListEl = document.querySelector(".songlist ul");
//         if (songListEl) {
//             for (const name of playsong) {
//                 const li = document.createElement("li");
//                 li.innerHTML = `
//                     <img src="MUSIC.svg" alt="">
//                     ${name.replaceAll("%20", " ")}
//                     <img src="SONG.svg" alt="">
//                 `;
//                 songListEl.appendChild(li);
//             }
//         }
//         songsLoaded = true;
//     }
// }


let songplaying = null;
let 

