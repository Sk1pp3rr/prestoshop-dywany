"""Modele walidacji danych dla scrapera dywanyluszczow.eu (Wymaganie W2)."""

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ProductVariant(BaseModel):
    """Wariant produktu (np. rozmiar dywanu 120x170 cm)."""

    size: str = Field(..., min_length=1, description="Rozmiar dywanu/chodnika, np. 120x170 cm")
    price_gross: float = Field(..., gt=0, description="Cena brutto w PLN")
    weight_kg: float = Field(..., gt=0, le=50.0, description="Waga wariantu w kg")
    stock_quantity: int = Field(default=5, ge=0, le=10, description="Stan magazynowy 0-10 szt.")


class ScrapedProduct(BaseModel):
    """Schemat walidacji produktu pobranego ze sklepu źródłowego (W2)."""

    external_id: str = Field(..., min_length=1, description="Unikalny identyfikator / SKU produktu")
    name: str = Field(..., min_length=2, description="Pełna nazwa produktu")
    description: str = Field(..., min_length=10, description="Opis produktu (HTML lub tekst)")
    category_path: list[str] = Field(
        ..., min_length=2, description="Ścieżka kategorii [Kategoria główna, Podkategoria]"
    )
    price_gross: float = Field(..., gt=0, description="Cena podstawowa brutto w PLN")
    vat_rate: int = Field(default=23, description="Stawka VAT w procentach (domyślnie 23%)")
    weight_kg: float = Field(..., gt=0, le=50.0, description="Waga jednostkowa produktu w kg")
    attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Cechy produktu (np. Wysokość runa, Skład, Kraj pochodzenia)",
    )
    image_urls: list[HttpUrl] = Field(
        ..., min_length=1, description="Adresy źródłowe zdjęć w wysokiej rozdzielczości"
    )
    variants: list[ProductVariant] = Field(
        default_factory=list, description="Opcjonalne warianty rozmiarowe produktu (D3)"
    )

    @field_validator("name", "description")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Pole tekstowe nie może być puste.")
        return cleaned
