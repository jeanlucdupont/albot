
<img width="1254" height="1254" alt="image" src="https://github.com/user-attachments/assets/02481388-1e42-4d2e-a849-9a152189baf1" />

# This is not a rabbit (And this is not stegano).

`brownrabbit.jpg` looks like an ordinary image. Open the same file with 7-Zip, however, and it reveals a ZIP archive containing `SecurityRabbits.exe`.

This is not steganography. Nothing is hidden in the image's pixels, and no encryption or special encoding is involved. The ZIP archive is simply appended to the image.

## How it works

Image viewers and ZIP readers parse files differently:

- An image viewer reads the image data from the beginning of the file and ignores the extra bytes that follow it.
- A ZIP reader searches near the end of the file for the ZIP directory and uses it to locate the archived content.

The same sequence of bytes can therefore be interpreted as an image by one application and as an archive by another.

The `.jpg` extension is not what makes the file an image. In this demonstration, the original image is a PNG renamed to `.jpg`; image viewers recognize its actual format from its contents.

## Files

- `brownrabbit-original.png` — the original image
- `SecurityRabbits.exe` — the demonstration file placed inside the archive
- `brownrabbit.jpg` — the resulting image/ZIP

## Build it

The following commands were run in Linux:

```bash
cp brownrabbit-original.png brownrabbit.jpg
zip hidden.zip SecurityRabbits.exe
printf '\n' >> brownrabbit.jpg
cat hidden.zip >> brownrabbit.jpg
```

The newline is not essential to the technique; it just separates the two byte sequences.

## Test it

Open `brownrabbit.jpg` normally and it displays the rabbit image.

Then inspect the exact same file with 7-Zip:

The archive reader finds the appended ZIP and lists `SecurityRabbits.exe`.

## What this does—and does not—demonstrate

This demonstrates why a filename extension, MIME type, or successful image preview is not sufficient to prove that a file contains only image data.

It does **not** make the executable run when the picture is opened. The archived file must still be discovered, extracted, and deliberately executed. This is a file-format parsing demonstration, not a remote-code-execution exploit.

## Security note

Do not extract or execute binaries from untrusted files. Files in this repository are provided for research and demonstration in a controlled environment.
