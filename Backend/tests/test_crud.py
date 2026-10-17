import crud
import schemas


def make(ticker, type_="Stock"):
    return schemas.InstrumentCreate(ticker=ticker, type=type_)


def test_create_uppercases_ticker(db):
    created = crud.create_instrument(db, make("aapl"))
    assert created.ticker == "AAPL"
    assert created.id is not None


def test_get_instruments_returns_all(db):
    crud.create_instrument(db, make("AAPL"))
    crud.create_instrument(db, make("BTC-USD", "Crypto"))
    assert {i.ticker for i in crud.get_instruments(db)} == {"AAPL", "BTC-USD"}


def test_get_instruments_empty(db):
    assert crud.get_instruments(db) == []


def test_get_by_ticker_is_case_insensitive(db):
    crud.create_instrument(db, make("AAPL"))
    assert crud.get_instrument_by_ticker(db, "aapl").ticker == "AAPL"


def test_get_by_ticker_missing_returns_none(db):
    assert crud.get_instrument_by_ticker(db, "NOPE") is None


def test_delete_existing_returns_true_and_removes(db):
    crud.create_instrument(db, make("AAPL"))
    assert crud.delete_instrument(db, "aapl") is True
    assert crud.get_instrument_by_ticker(db, "AAPL") is None


def test_delete_missing_returns_false(db):
    assert crud.delete_instrument(db, "NOPE") is False
