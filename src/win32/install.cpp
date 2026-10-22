// Ties the GUI subsystem into the emulator.
#include "emulator.h"
#include "gui.h"

namespace x86emu::win32 {

void install_scroll_api(Emulator& e);
void install_resources(Emulator& e);
void install_ansi(Emulator& e);

void install_all(Emulator& e) {
    install_kernel_extra(e);
    install_registry(e);
    install_gdi(e);
    install_user(e);
    install_scroll_api(e);
    install_resources(e);
    install_menu(e);
    install_dialog(e);
    install_controls(e);
    install_shell_ole(e);
    install_ansi(e);
}

}  // namespace x86emu::win32

void x86emu::Emulator::install_gui_hooks() { win32::install_all(*this); }
