from django.urls import path

from .views import (
    LinkCreateView,
    LinkDeleteView,
    LinkDetailView,
    LinkListView,
    LinkPublicRedirectView,
    LinkUpdateView,
)

urlpatterns = [
    path("links/", LinkListView.as_view(), name="link_list"),
    path("links/new/", LinkCreateView.as_view(), name="link_create"),
    path("links/<int:pk>/", LinkDetailView.as_view(), name="link_detail"),
    path("links/<int:pk>/edit/", LinkUpdateView.as_view(), name="link_update"),
    path("links/<int:pk>/delete/", LinkDeleteView.as_view(), name="link_delete"),
    path(
        "<str:username>/<str:slug>/",
        LinkPublicRedirectView.as_view(),
        name="link_redirect",
    ),
]
