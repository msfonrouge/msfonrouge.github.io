# msfonrouge.github.io

Personal site of Maximo Segundo Fonrouge. GitHub Pages publishes the `main` branch as is. There is no build step.

- `new/` is the new site (work in progress). Its live address is https://msfonrouge.github.io/new/.
- The root `index.html` is the old portfolio. Keep it until Segun says to switch.
- `new/img/beach-night*.jpg` is the scene at the top. It is rendered in Blender by `scene/build.py`, from code only.

## Rules

- Write in English. Keep the tone calm and personal, like felixrieseberg.com. No sales language.
- Keep the page as one HTML file with inline CSS. No frameworks.
- Check every change at 390 px and 1440 px wide. There must be no sideways scroll.
- Text placeholders still to replace: the Writing titles, and the links that point to `#`.

## Rendering the scene

    blender -b -P scene/build.py -- --time night --out /tmp/night.png --width 1920 --height 1080 --samples 128
    sips -s format jpeg -s formatOptions 82 /tmp/night.png --out new/img/beach-night.jpg
    sips -Z 1100 -s format jpeg -s formatOptions 80 /tmp/night.png --out new/img/beach-night-small.jpg

A test render (`--width 800 --height 450 --samples 32`) takes about 15 s on the Mac. A full render takes about 3.5 min.
In a cloud session without a GPU it is much slower. There, change only the page, or install Blender first (`apt-get install blender`).
