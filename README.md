Contained in this repository are two different versions of my Investment Operations Dashboard.

Investment_Ops_Dashboard_Sanitized is all human input. It's a very small file that's easy to run and change to fit your needs. Just download it and run it, and it will pop up in your browser.

Investment_Ops_Dashboard_Ai.html is the same dashboard with AI SOP generation, so it can draft your SOPs for you. It takes some setup, and it's Windows only.

Everything in both versions is sample data and stays on your computer. Don't enter client names, account numbers, or anything confidential.

Running the dashboard with AI SOP generation

You'll need Python installed, since the setup scripts are written in it. Then download these four files into one folder:

Investment_Ops_Dashboard_Ai.html
Start SOP Writer.bat
install_llama.py
start_qwen.py

You'll also need a copy of Qwen from Hugging Face (huggingface.co). Download the GGUF version in Q4_K_M and put the .gguf file in the same folder. Pick a size that fits your computer, since the model has to fit in your RAM or graphics memory.

Qwen is the AI model. To run it you need llama.cpp, a small program that loads the model and serves it from your PC. You don't have to hunt it down. Open PowerShell in your folder and run:

python install_llama.py

That downloads llama.cpp into the folder and picks the right version for your hardware, NVIDIA CUDA or Vulkan. If it picks wrong or fails, run python install_llama.py --backend vulkan, which works on NVIDIA, AMD, and Intel graphics.

Then double-click Start SOP Writer.bat. It starts Qwen and opens the dashboard. Keep the black window open while you work, and close it when you're done so your memory is freed up.

Open an SOP on any task, wait for the AI panel to say it's connected, add some notes, and click Draft SOP, and you should be good to go.

How it works

Starting the .bat runs llama.cpp as a server on your own PC at 127.0.0.1:8080, an address that only your computer can reach. The dashboard talks to that server, so your notes and the drafts never leave your machine.

Good to know

Always read what the AI writes. A small local model can get details wrong, and anything it wasn't told shows up as [CONFIRM: ...] for you to fill in. The more detail you give it, the better the draft.

If it won't start, run python start_qwen.py --info in PowerShell. It shows your hardware, the model it found, and whether it should fit.
