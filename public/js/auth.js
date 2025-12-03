
import { supabase } from "./supabase.js";

async function syncButtons(){
    const { data } = await supabase.auth.getUser();
    const logged = !!data.user;
    document.querySelectorAll(".login-btn").forEach(b=>b.style.display= logged?"none":"inline-block");
    document.querySelectorAll(".logout-btn").forEach(b=>b.style.display= logged?"inline-block":"none");
}
async function logout(){ await supabase.auth.signOut(); location.reload(); }

document.addEventListener("DOMContentLoaded", syncButtons);
document.querySelectorAll(".logout-btn").forEach(b=>b.onclick=logout);
