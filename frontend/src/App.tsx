import { useEffect, useState } from 'preact/hooks';
import './App.css';

const App = () => {
  const [meta, setMeta] = useState({});

  const [loading, setLoading] = useState(true);
  const [edit, setEdit] = useState(true);

  const [street, setStreet] = useState('');
  const [disposalTypes, setDisposalTypes] = useState([]);
  const [parties, setParties] = useState([]);

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
    }

    if (edit) {
      setEdit(edit === '1');
    }
  }

  function changePartyName(idx, name) {
    const newParties = [...parties];
    newParties[idx] = name;
    setParties(newParties);
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
          <div className="formLayout">
            <div className="subheadline">
              <div className="container">
                {edit ? (
                  <select
                    onChange={(e) => setStreet(e.currentTarget.value)}
                    value={street}
                  >
                    {meta.streets.map((street) => (
                      <option key={street}>{street}</option>
                    ))}
                  </select>
                ) : (
                  <span>{street}</span>
                )}
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
                      )}&weekModulo=${idx + 1}&parties=${parties.length}`}
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
          </div>
          <div class="more container">
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
        </>
      )}
    </>
  );
};

export default App;
