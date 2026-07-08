# STM32 E-Dice (Electronic Dice)

A complete hardware and software project that turns an STM32 Nucleo board and an accelerometer into a functional, 3D-rendered Electronic Dice. The physical cube's orientation is sent over USB to a sleek, dark-themed Python GUI that displays the corresponding dice face in real-time.

## Hardware Requirements

*   **Microcontroller:** STM32L476RG Nucleo-64 Board
*   **Sensor Shield:** ST X-NUCLEO-IKS01A3 (Motion MEMS & Environmental Sensor Expansion Board)
*   **Sensor Used:** LSM6DSO (3D Accelerometer)
*   **Physical Enclosure:** A 6-sided cube box to hold the hardware, numbered 1 through 6 like a standard die (opposite faces must add up to 7).

## How It Works

1.  **Hardware:** The IKS01A3 shield is stacked on top of the Nucleo-64 board.
2.  **Firmware (C):** The STM32 reads the X, Y, and Z gravity vectors from the LSM6DSO accelerometer via **I2C1** (104 Hz, ±2g scale). 
3.  **Communication:** The raw milligravity (mg) data is formatted into a string (`X:-989, Y:14, Z:-89`) and transmitted to the PC via **USART2** (115200 baud) over the USB Virtual COM port.
4.  **Software (Python):** A custom Tkinter GUI reads the serial stream, determines the dominant gravity axis, and renders the correct dice face with smooth micro-animations.

## Firmware Setup (STM32CubeIDE)

The firmware is designed to be highly robust and bypasses common Nucleo clock issues by utilizing the internal MSI oscillator.

1. Create a new STM32 project for the **NUCLEO-L476RG** in STM32CubeIDE.
2. Open the `.ioc` file and configure:
   *   **I2C1:** PB8 (SCL), PB9 (SDA) — Fast Mode.
   *   **USART2:** PA2 (TX), PA3 (RX) — 115200 Baud (usually enabled by default).
   *   **GPIO:** PA5 (User LED LD2) — Output.
3. Replace the contents of `Core/Src/main.c` with the provided `main.c` file from this repository.
4. Build the project and click **Run** to flash the board.
5. **Success Indicator:** The green LED (LD2) will blink exactly 4 times on startup, indicating the accelerometer was successfully detected and initialized.


## Software Setup (Python GUI)

The GUI is a modern, Retina-ready desktop application built with Python and Tkinter.

### Prerequisites
You need Python 3 installed on your system (macOS/Windows/Linux). 
Install the required Serial library:
```bash
pip install pyserial
```
Install the required Tkinter library:
```bash
pip install tkinter
```
### Running the GUI
Run the Python application:
```
bash
python e_dice_gui.py
```

### Connecting
- Look at the Connection Panel at the bottom of the window.
- Select your board's COM Port from the dropdown (e.g., COM3 on Windows, or /dev/cu.usbmodem... on macOS).
- Ensure the Baud rate is set to 115200.
- Click ⚡ Connect. You should instantly see live accelerometer data and the rendered dice face!

## Calibration (Mapping Axes to Faces)
Because everyone mounts their board inside their physical cube differently, you need to tell the software which axis corresponds to which physical face on your box.

1. Open Edice_gui.py in any text editor.
2. Locate the FACE_MAP dictionary at the top of the file:

FACE_MAP = {
    'Z+': 1,   'Z-': 6,
    'Y+': 2,   'Y-': 5,
    'X+': 3,   'X-': 4,
}
3. Run the GUI and connect to the board.
4. Place your physical cube on the table with Face 1 pointing straight UP.
5. Look at the GUI's accelerometer bars. One axis will show a strong pull (approx +1000 mg or -1000 mg).
- Example: If the X bar reads -989 mg, then X- is Face 1. Change the map so 'X-': 1, and therefore 'X+': 6 (since opposite faces must add to 7).
6. Repeat this process for Face 2 and Face 3 until all 6 faces are mapped perfectly to your physical cube!