from organizer_ict.views import gestione_progetti as organizer_ict_gestione_progetti


def crea_vista_organizer_ict(page, current_user=None):
    # Bridge iniziale: il modulo Organizer ICT espone la vista principale.
    return organizer_ict_gestione_progetti.crea_vista_gestione_progetti(page, current_user=current_user)
