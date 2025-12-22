import { useEffect, useState } from 'preact/hooks';
import './App.css';

const App = () => {
  const [meta, setMeta] = useState({});

  const [loading, setLoading] = useState(true);
  const [edit, setEdit] = useState(true);

  const [street, setStreet] = useState('');
  const [disposalTypes, setDisposalTypes] = useState([]);
  const [parties, setParties] = useState([]);

  const [year, setYear] = useState(2025);

  function decodeFromUrl() {
    const url = new URL(window.location.href);
    const data = url.searchParams.get('data');
    const edit = url.searchParams.get('edit');

    if (data) {
      const decoded = atob(data);
      const parsed = JSON.parse(decoded);

      setStreet(parsed.street);
      setDisposalTypes(parsed.disposal_types);
      setParties(parsed.parties);
      setYear(parsed.year || (parsed.parties ? 2025 : new Date().getFullYear));
    }

    if (edit) {
      setEdit(edit === '1');
    }
  }

  function getISOWeek(date: Date) {
    const tempDate = new Date(date.getTime());
    tempDate.setDate(tempDate.getDate() + 4 - (tempDate.getDay() || 7));
    const yearStart = new Date(tempDate.getFullYear(), 0, 1);
    return Math.ceil((((tempDate - yearStart) / 86400000) + 1) / 7);
  }

  function getWeeksInYear(year: number) {
    const d = new Date(year, 11, 31);
    const week = getISOWeek(d);
    return week === 1 ? getISOWeek(new Date(year, 11, 24)) : week;
  }

  function changePartyName(idx, name) {
    const newParties = [...parties];
    newParties[idx] = name;
    setParties(newParties);
  }

  function reorderParties(newYear: number) {
    if (newYear === year) return;
    let currentYear = year;
    let currentParties = [...parties];
    if (newYear < year) {
      while (currentYear > newYear) {
        const firstPartyInLastYear = getWeeksInYear(currentYear - 1) % currentParties.length;
        currentParties = [...currentParties.slice(currentParties.length - firstPartyInLastYear), ...currentParties.slice(0, currentParties.length - firstPartyInLastYear)];
        currentYear--;
      }
    } else {
      while (currentYear < newYear) {
        const lastParty = getWeeksInYear(currentYear) % currentParties.length;
        currentParties = [...currentParties.slice(lastParty), ...currentParties.slice(0, lastParty)];
        currentYear++;
      }
    }
    setParties(currentParties);
    setYear(newYear);
  }

  useEffect(() => {
    decodeFromUrl();

    fetch('/api/meta')
      .then((res) => res.json())
      .then((data) => {
        setMeta(data);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);

    const data = {
      street: street,
      disposal_types: disposalTypes,
      parties: parties,
      year: year,
    };

    url.searchParams.set('data', btoa(JSON.stringify(data)));
    url.searchParams.set('edit', edit ? '1' : '0');
    window.history.pushState({}, '', url);
  }, [street, disposalTypes, parties, edit]);

  return (
    <>
      <div className="headline">
        <h1 class="container">EAD Splitter</h1>
      </div>
      {loading ? (
        <div className="lds-container">
          <div className="lds-dual-ring" />
        </div>
      ) : (
        <>
          <div className="subheadline">
            <div className="container">
              <div className="sub-flex">
                {edit ? (
                  <>
                    <label htmlFor="streetSelect">
                      <span>
                        Straße
                      </span>
                      <select
                        onChange={(e) => setStreet(e.currentTarget.value)}
                        value={street}
                        className="streetSelect"
                      >
                        {meta.streets.map((street) => (
                          <option key={street}>{street}</option>
                        ))}
                      </select>
                    </label>
                    <label htmlFor="yearSelect">
                      <span>Jahr</span>
                      <select onChange={(e) => reorderParties(e.currentTarget.value)} value={year} className="yearSelect">
                        {meta.years.map((year) => (
                          <option key={year}>{year}</option>
                        ))}
                      </select>
                    </label>
                  </>
                ) : (
                  <>
                    <span>
                      {street}
                    </span>
                    <span class="year"> {year}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="container">
            <h2 class="headlineSection">Abfallarten im Kalender</h2>
            <div className="formLayoutDisposal">
              {meta.disposal_types.map((disposal_type, idx) => (
                <>
                  <input
                    type="checkbox"
                    onChange={(e) => {
                      const checked = e.currentTarget.checked;
                      const newDisposalTypes = checked
                        ? [...disposalTypes, disposal_type.short]
                        : disposalTypes.filter(
                          (dt) => dt !== disposal_type.short,
                        );
                      setDisposalTypes(newDisposalTypes);
                    }}
                    key={disposal_type.short}
                    id={disposal_type.short}
                    name={disposal_type.short}
                    checked={disposalTypes.includes(disposal_type.short)}
                    value={disposal_type.short}
                  />
                  <label
                    className="formLayoutDisposalEl"
                    key={disposal_type.short}
                    htmlFor={disposal_type.short}
                    style={`--disp-color: ${disposal_type.color};`}
                  >
                    {disposal_type.name}
                  </label>
                </>
              ))}
            </div>
            <h2 class="headlineSection">Parteien</h2>
            <div
              className={edit ? 'formLayoutParties' : 'formLayoutPartiesView'}
            >
              {parties.map((party, idx) => (
                <div
                  className={edit ? 'formLayoutParty' : 'formLayoutPartyView'}
                  key={party}
                >
                  {edit && <span>Partei {idx + 1}</span>}
                  {edit ? (
                    <input
                      type="text"
                      value={party}
                      onChange={(e) =>
                        changePartyName(idx, e.currentTarget.value)
                      }
                    />
                  ) : (
                    <span className="partyName">{party}</span>
                  )}
                  <span className="partyWeek">
                    KW{' '}
                    {[idx, idx, idx].map(
                      (idx, idx1) => `${idx + 1 + idx1 * parties.length}, `,
                    )}
                    ...
                  </span>
                  <a
                    className="btn btn--download"
                    href={`/api/download?street=${encodeURIComponent(
                      street,
                    )}&disposal_types=${encodeURIComponent(
                      disposalTypes.join(','),
                    )}&weekModulo=${idx + 1}&parties=${parties.length}&year=${year}`}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width={24}
                      height={24}
                      viewBox="0 0 24 24"
                    >
                      <title>Download Icon</title>
                      <path
                        fill="currentColor"
                        d="M5 20h14v-2H5m14-9h-4V3H9v6H5l7 7z"
                      />
                    </svg>{' '}
                    Download .ics
                  </a>
                </div>
              ))}
            </div>
            {edit && (
              <span className="buttonRow">
                <button
                  type="button"
                  className="btn-add"
                  onClick={() => setParties([...parties, ''])}
                >
                  Hinzufügen
                </button>
                <button
                  type="button"
                  className="btn-delete"
                  onClick={() => setParties([])}
                >
                  Liste leeren
                </button>
              </span>
            )}
          </div>

          <footer className="container">
            <div className="footer">
              <span>
                Made with ❤️ by{' '}
                <a href="https://thilo-billerbeck.com ">Thilo Billerbeck</a> -{' '}
                <a
                  href="https://thilo-billerbeck.com/impressum/"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  Impressum
                </a>{' '}
                -{' '}
                <a
                  href="https://github.com/thilobillerbeck/ead-splitter"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  Source Code
                </a>
              </span>
              <button onClick={() => setEdit(!edit)} type="button">
                {edit ? 'zur Leseansicht' : 'bearbeiten'}
              </button>
            </div>
          </footer>
        </>
      )
      }
    </>
  );
};

export default App;
